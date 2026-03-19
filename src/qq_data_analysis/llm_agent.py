from __future__ import annotations

import json
import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

import httpx
from pydantic import BaseModel, Field

try:
    from qq_data_process.utils import preview_text
except ImportError:  # pragma: no cover - smoke harness fallback path
    def preview_text(value: str | None, limit: int = 100) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return f"{text[: max(0, limit - 1)].rstrip()}…"


_GROUNDING_IMPORT_ERROR: Exception | None = None
try:
    from .agents import BaseAnalysisAgent
    from .models import (
        AnalysisAgentOutput,
        AnalysisEvidenceItem,
        AnalysisMaterials,
        AnalysisMessageRecord,
    )
except ImportError as exc:  # pragma: no cover - smoke harness fallback path
    _GROUNDING_IMPORT_ERROR = exc

    class BaseAnalysisAgent:  # type: ignore[no-redef]
        pass

    AnalysisAgentOutput = Any  # type: ignore[assignment]
    AnalysisEvidenceItem = Any  # type: ignore[assignment]
    AnalysisMaterials = Any  # type: ignore[assignment]
    AnalysisMessageRecord = Any  # type: ignore[assignment]


class DeepSeekRuntimeConfig(BaseModel):
    api_key: str
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-reasoner"
    proxy_url: str | None = None
    temperature: float = 0.2
    timeout_s: float = 180.0
    idle_timeout_s: float = 60.0


class OpenAICompatibleRuntimeConfig(BaseModel):
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-5.4"
    proxy_url: str | None = None
    temperature: float | None = None
    reasoning_effort: str | None = None
    timeout_s: float = 180.0
    idle_timeout_s: float = 60.0


def _httpx_timeout_for_runtime(config: Any) -> httpx.Timeout:
    base_timeout = max(float(getattr(config, "timeout_s", 180.0) or 180.0), 1.0)
    idle_timeout = max(
        float(getattr(config, "idle_timeout_s", base_timeout) or base_timeout),
        1.0,
    )
    return httpx.Timeout(
        connect=base_timeout,
        read=idle_timeout,
        write=base_timeout,
        pool=base_timeout,
    )


def apply_openai_prompt_family_defaults(
    config: OpenAICompatibleRuntimeConfig,
    *,
    prompt_family: str | None = None,
) -> OpenAICompatibleRuntimeConfig:
    normalized = (prompt_family or "").strip().lower()
    if not normalized.startswith("benshi_master"):
        return config
    updates: dict[str, Any] = {}
    if config.reasoning_effort is None:
        updates["reasoning_effort"] = "medium"
    if config.temperature is None:
        updates["temperature"] = 0.0
    if not updates:
        return config
    return config.model_copy(update=updates)


class MultimodalInputImage(BaseModel):
    path: Path
    mime_type: str | None = None
    label: str | None = None


class MultimodalSmokePack(BaseModel):
    provider: str | None = None
    model: str | None = None
    system_prompt: str = ""
    user_prompt: str
    images: list[MultimodalInputImage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


@dataclass(slots=True)
class DenseSlicePlan:
    source_label: str
    source_start_iso: str
    source_end_iso: str
    source_message_count: int
    selected_messages: list[AnalysisMessageRecord]
    selected_start_iso: str
    selected_end_iso: str
    estimated_input_tokens: int
    max_output_tokens: int
    trimmed: bool
    target_message_cap: int
    rendered_messages: list[AnalysisMessageRecord]
    rendered_message_count: int


@dataclass(slots=True)
class LlmUsageSnapshot:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    reasoning_tokens: int
    cached_tokens: int


@dataclass(slots=True)
class LlmResponseBundle:
    parsed_payload: dict[str, Any]
    raw_text: str
    reasoning_text: str
    finish_reason: str
    usage: LlmUsageSnapshot
    raw_response: dict[str, Any]


class LlmClient(Protocol):
    def analyze(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        stream_callback: Callable[[str, str], None] | None = None,
    ) -> LlmResponseBundle: ...


class MultimodalLlmClient(Protocol):
    provider_name: str

    def analyze_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        images: Iterable[MultimodalInputImage],
        max_output_tokens: int,
        stream_callback: Callable[[str, str], None] | None = None,
    ) -> LlmResponseBundle: ...


def load_deepseek_runtime_config(path: Path) -> DeepSeekRuntimeConfig:
    if not path.exists():
        raise RuntimeError(
            f"DeepSeek config file was not found: {path}. Fill state/config/llm.local.json first."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("deepseek", {})
    config = DeepSeekRuntimeConfig.model_validate(raw)
    if not config.api_key or "PASTE_YOUR_DEEPSEEK_API_KEY_HERE" in config.api_key:
        raise RuntimeError(
            f"DeepSeek api_key is still a placeholder in {path}. Fill it before running LLM analysis."
        )
    return config


def load_openai_compatible_runtime_config(path: Path) -> OpenAICompatibleRuntimeConfig:
    if not path.exists():
        raise RuntimeError(
            f"OpenAI-compatible config file was not found: {path}. Fill state/config/llm.local.json first."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("openai_compatible", {})
    config = OpenAICompatibleRuntimeConfig.model_validate(raw)
    if not config.api_key or "PASTE_YOUR" in config.api_key:
        raise RuntimeError(
            f"OpenAI-compatible api_key is still a placeholder in {path}. Fill it before running LLM analysis."
        )
    return config


def load_multimodal_runtime_config(
    path: Path,
    *,
    provider: str = "openai_compatible",
) -> OpenAICompatibleRuntimeConfig | DeepSeekRuntimeConfig:
    resolved = provider.strip().lower()
    if resolved == "openai_compatible":
        return load_openai_compatible_runtime_config(path)
    if resolved == "deepseek":
        return load_deepseek_runtime_config(path)
    raise ValueError(f"Unsupported multimodal provider: {provider}")


def load_multimodal_client(
    path: Path,
    *,
    provider: str = "openai_compatible",
    model: str | None = None,
) -> MultimodalLlmClient:
    resolved = provider.strip().lower()
    if resolved == "openai_compatible":
        config = load_openai_compatible_runtime_config(path)
        if model:
            config = config.model_copy(update={"model": model})
        return OpenAICompatibleAnalysisClient(config)
    if resolved == "deepseek":
        raise RuntimeError(
            "Provider 'deepseek' is currently text-only in this smoke harness. "
            "Use provider='openai_compatible' for GPT-5.4 relay multimodal tests."
        )
    raise ValueError(f"Unsupported multimodal provider: {provider}")


def load_multimodal_smoke_pack(path: Path) -> MultimodalSmokePack:
    if not path.exists():
        raise FileNotFoundError(f"Multimodal smoke pack does not exist: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    normalized = dict(raw)
    normalized_images: list[dict[str, Any]] = []
    for item in raw.get("images", []) or []:
        if isinstance(item, str):
            normalized_images.append({"path": item})
            continue
        if isinstance(item, dict):
            normalized_images.append(item)
            continue
        raise TypeError(
            "Multimodal smoke pack images must be strings or objects with a 'path' field."
        )
    normalized["images"] = normalized_images
    pack = MultimodalSmokePack.model_validate(normalized)
    resolved_images = [
        image.model_copy(
            update={
                "path": (path.parent / image.path).resolve()
                if not image.path.is_absolute()
                else image.path.resolve()
            }
        )
        for image in pack.images
    ]
    return pack.model_copy(update={"images": resolved_images})


class DeepSeekAnalysisClient:
    def __init__(self, config: DeepSeekRuntimeConfig) -> None:
        self.config = config

    def analyze(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
    ) -> LlmResponseBundle:
        payload = {
            "model": self.config.model,
            "max_tokens": max_output_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        return self._execute_request(payload, expect_json_object=True)

    def analyze_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        stream_callback: Callable[[str, str], None] | None = None,
    ) -> LlmResponseBundle:
        payload = {
            "model": self.config.model,
            "max_tokens": max_output_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if stream_callback is not None:
            return self._execute_streaming_text_request(
                payload,
                stream_callback=stream_callback,
            )
        return self._execute_request(payload, expect_json_object=False)

    def _execute_streaming_text_request(
        self,
        payload: dict[str, Any],
        *,
        stream_callback: Callable[[str, str], None],
    ) -> LlmResponseBundle:
        if self.config.model != "deepseek-reasoner":
            payload["temperature"] = self.config.temperature
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
        client_kwargs: dict[str, Any] = {
            "timeout": _httpx_timeout_for_runtime(self.config),
            "trust_env": False,
        }
        if self.config.proxy_url:
            client_kwargs["proxy"] = self.config.proxy_url

        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        finish_reason = ""
        usage = LlmUsageSnapshot(
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            reasoning_tokens=0,
            cached_tokens=0,
        )
        last_body: dict[str, Any] = {}

        with httpx.Client(**client_kwargs) as client:
            with client.stream(
                "POST",
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if not raw or raw == "[DONE]":
                        continue
                    body = json.loads(raw)
                    last_body = body
                    choice = body.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    content_piece = str(delta.get("content", "") or "")
                    reasoning_piece = str(
                        delta.get("reasoning_content", delta.get("reasoning", "")) or ""
                    )
                    if reasoning_piece:
                        reasoning_parts.append(reasoning_piece)
                        stream_callback("reasoning", reasoning_piece)
                    if content_piece:
                        content_parts.append(content_piece)
                        stream_callback("content", content_piece)
                    if choice.get("finish_reason"):
                        finish_reason = str(choice.get("finish_reason") or "")
                    if body.get("usage"):
                        usage = _extract_usage(body)

        raw_text = "".join(content_parts).strip()
        reasoning_text = "".join(reasoning_parts).strip()
        return LlmResponseBundle(
            parsed_payload={},
            raw_text=raw_text,
            reasoning_text=reasoning_text,
            finish_reason=finish_reason,
            usage=usage,
            raw_response=last_body,
        )

    def _execute_request(
        self,
        payload: dict[str, Any],
        *,
        expect_json_object: bool,
    ) -> LlmResponseBundle:
        if self.config.model != "deepseek-reasoner":
            payload["temperature"] = self.config.temperature
        client_kwargs: dict[str, Any] = {
            "timeout": _httpx_timeout_for_runtime(self.config),
            "trust_env": False,
        }
        if self.config.proxy_url:
            client_kwargs["proxy"] = self.config.proxy_url

        with httpx.Client(**client_kwargs) as client:
            response = client.post(
                f"{self.config.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()

        choice = body.get("choices", [{}])[0]
        message = choice.get("message", {})
        raw_text = str(message.get("content", "")).strip()
        reasoning_text = str(message.get("reasoning_content", "")).strip()
        parsed = _extract_json_object(raw_text) if expect_json_object else {}
        usage = _extract_usage(body)
        return LlmResponseBundle(
            parsed_payload=parsed,
            raw_text=raw_text,
            reasoning_text=reasoning_text,
            finish_reason=str(choice.get("finish_reason", "")).strip(),
            usage=usage,
            raw_response=body,
        )


class OpenAICompatibleAnalysisClient:
    provider_name = "openai_compatible"

    def __init__(self, config: OpenAICompatibleRuntimeConfig) -> None:
        self.config = config

    def analyze(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
    ) -> LlmResponseBundle:
        bundle = self._execute_request(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=max_output_tokens,
        )
        bundle.parsed_payload = _extract_json_object(bundle.raw_text)
        return bundle

    def analyze_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
        stream_callback: Callable[[str, str], None] | None = None,
    ) -> LlmResponseBundle:
        fallback_payload = _build_openai_chat_text_payload(
            model=self.config.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=max_output_tokens,
            temperature=self.config.temperature,
            reasoning_effort=self.config.reasoning_effort,
            stream=stream_callback is not None,
        )
        if stream_callback is not None:
            payload: dict[str, Any] = {
                "model": self.config.model,
                "instructions": system_prompt,
                "input": user_prompt,
                "max_output_tokens": max_output_tokens,
            }
            self._apply_openai_optional_controls(payload, responses_api=True)
            payload["stream"] = True
            return self._execute_streaming_payload(
                payload,
                stream_callback=stream_callback,
                fallback_payload=fallback_payload,
            )
        return self._execute_request(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=max_output_tokens,
        )

    def analyze_multimodal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        images: Iterable[MultimodalInputImage],
        max_output_tokens: int,
        stream_callback: Callable[[str, str], None] | None = None,
    ) -> LlmResponseBundle:
        image_list = list(images)
        content: list[dict[str, Any]] = []
        if user_prompt.strip():
            content.append({"type": "input_text", "text": user_prompt.strip()})
        for index, image in enumerate(image_list, start=1):
            if image.label:
                content.append(
                    {
                        "type": "input_text",
                        "text": f"[image {index} label] {image.label.strip()}",
                    }
                )
            content.append(_build_openai_input_image(image))

        if not content:
            raise ValueError("analyze_multimodal requires at least one text or image input")

        payload: dict[str, Any] = {
            "model": self.config.model,
            "instructions": system_prompt,
            "input": [{"role": "user", "content": content}],
            "max_output_tokens": max_output_tokens,
        }
        fallback_payload = _build_openai_chat_multimodal_payload(
            model=self.config.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            images=image_list,
            max_output_tokens=max_output_tokens,
            temperature=self.config.temperature,
            reasoning_effort=self.config.reasoning_effort,
            stream=stream_callback is not None,
        )
        self._apply_openai_optional_controls(payload, responses_api=True)
        if stream_callback is not None:
            payload["stream"] = True
            return self._execute_streaming_payload(
                payload,
                stream_callback=stream_callback,
                fallback_payload=fallback_payload,
            )
        return self._execute_payload(payload, fallback_payload=fallback_payload)

    def caption_image(
        self,
        *,
        image_path: Path,
        prompt: str,
        max_output_tokens: int = 220,
        stream_callback: Callable[[str, str], None] | None = None,
    ) -> LlmResponseBundle:
        mime_type, _ = mimetypes.guess_type(str(image_path))
        if not mime_type:
            mime_type = "image/jpeg"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        payload: dict[str, Any] = {
            "model": self.config.model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:{mime_type};base64,{encoded}",
                        },
                    ],
                }
            ],
            "max_output_tokens": max_output_tokens,
        }
        fallback_payload = _build_openai_chat_multimodal_payload(
            model=self.config.model,
            system_prompt="",
            user_prompt=prompt,
            images=[MultimodalInputImage(path=image_path, mime_type=mime_type)],
            max_output_tokens=max_output_tokens,
            temperature=self.config.temperature,
            reasoning_effort=self.config.reasoning_effort,
            stream=stream_callback is not None,
        )
        self._apply_openai_optional_controls(payload, responses_api=True)
        if stream_callback is not None:
            payload["stream"] = True
            return self._execute_streaming_payload(
                payload,
                stream_callback=stream_callback,
                fallback_payload=fallback_payload,
            )
        return self._execute_payload(payload, fallback_payload=fallback_payload)

    def _execute_request(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_output_tokens: int,
    ) -> LlmResponseBundle:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "instructions": system_prompt,
            "input": user_prompt,
            "max_output_tokens": max_output_tokens,
        }
        fallback_payload = _build_openai_chat_text_payload(
            model=self.config.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=max_output_tokens,
            temperature=self.config.temperature,
            reasoning_effort=self.config.reasoning_effort,
        )
        self._apply_openai_optional_controls(payload, responses_api=True)
        return self._execute_payload(payload, fallback_payload=fallback_payload)

    def _execute_payload(
        self,
        payload: dict[str, Any],
        *,
        fallback_payload: dict[str, Any] | None = None,
    ) -> LlmResponseBundle:
        client_kwargs: dict[str, Any] = {
            "timeout": _httpx_timeout_for_runtime(self.config),
            "trust_env": False,
        }
        if self.config.proxy_url:
            client_kwargs["proxy"] = self.config.proxy_url

        with httpx.Client(**client_kwargs) as client:
            try:
                response = client.post(
                    f"{self.config.base_url.rstrip('/')}/responses",
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
            except httpx.HTTPStatusError as exc:
                if not _should_fallback_to_chat_completions(exc):
                    raise
                if fallback_payload is None:
                    raise
                return self._execute_chat_payload(client, fallback_payload)

        return LlmResponseBundle(
            parsed_payload={},
            raw_text=_extract_openai_output_text(body),
            reasoning_text="",
            finish_reason=str(body.get("status", "")).strip(),
            usage=_extract_openai_usage(body),
            raw_response=body,
        )

    def _execute_streaming_payload(
        self,
        payload: dict[str, Any],
        *,
        stream_callback: Callable[[str, str], None],
        fallback_payload: dict[str, Any] | None = None,
    ) -> LlmResponseBundle:
        client_kwargs: dict[str, Any] = {
            "timeout": _httpx_timeout_for_runtime(self.config),
            "trust_env": False,
        }
        if self.config.proxy_url:
            client_kwargs["proxy"] = self.config.proxy_url

        content_parts: list[str] = []
        usage = LlmUsageSnapshot(
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            reasoning_tokens=0,
            cached_tokens=0,
        )
        last_body: dict[str, Any] = {}

        with httpx.Client(**client_kwargs) as client:
            try:
                with client.stream(
                    "POST",
                    f"{self.config.base_url.rstrip('/')}/responses",
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        raw = line[5:].strip()
                        if not raw:
                            continue
                        body = json.loads(raw)
                        last_body = body
                        event_type = str(body.get("type") or "")
                        if event_type == "response.output_text.delta":
                            piece = str(body.get("delta") or "")
                            if piece:
                                content_parts.append(piece)
                                stream_callback("content", piece)
                        elif event_type == "response.completed":
                            response_body = body.get("response", {})
                            if response_body:
                                last_body = response_body
                                usage = _extract_openai_usage(response_body)
            except httpx.HTTPStatusError as exc:
                if not _should_fallback_to_chat_completions(exc):
                    raise
                if fallback_payload is None:
                    raise
                return self._execute_chat_streaming_payload(
                    client,
                    fallback_payload,
                    stream_callback=stream_callback,
                )

        return LlmResponseBundle(
            parsed_payload={},
            raw_text="".join(content_parts).strip(),
            reasoning_text="",
            finish_reason=str(last_body.get("status", "")).strip(),
            usage=usage,
            raw_response=last_body,
        )

    def _execute_chat_payload(
        self,
        client: httpx.Client,
        payload: dict[str, Any],
    ) -> LlmResponseBundle:
        response = client.post(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
        choice = body.get("choices", [{}])[0]
        message = choice.get("message", {}) or {}
        return LlmResponseBundle(
            parsed_payload={},
            raw_text=_extract_chat_completion_text(message),
            reasoning_text=_extract_chat_completion_reasoning(message),
            finish_reason=str(choice.get("finish_reason", "") or "").strip(),
            usage=_extract_usage(body),
            raw_response=body,
        )

    def _execute_chat_streaming_payload(
        self,
        client: httpx.Client,
        payload: dict[str, Any],
        *,
        stream_callback: Callable[[str, str], None],
    ) -> LlmResponseBundle:
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        finish_reason = ""
        usage = LlmUsageSnapshot(
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            reasoning_tokens=0,
            cached_tokens=0,
        )
        last_body: dict[str, Any] = {}
        with client.stream(
            "POST",
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue
                body = json.loads(raw)
                last_body = body
                choice = body.get("choices", [{}])[0]
                delta = choice.get("delta", {}) or {}
                content_piece = _extract_chat_completion_text(delta)
                reasoning_piece = _extract_chat_completion_reasoning(delta)
                if reasoning_piece:
                    reasoning_parts.append(reasoning_piece)
                    stream_callback("reasoning", reasoning_piece)
                if content_piece:
                    content_parts.append(content_piece)
                    stream_callback("content", content_piece)
                if choice.get("finish_reason"):
                    finish_reason = str(choice.get("finish_reason") or "")
                if body.get("usage"):
                    usage = _extract_usage(body)
        return LlmResponseBundle(
            parsed_payload={},
            raw_text="".join(content_parts).strip(),
            reasoning_text="".join(reasoning_parts).strip(),
            finish_reason=finish_reason,
            usage=usage,
            raw_response=last_body,
        )

    def _apply_openai_optional_controls(
        self,
        payload: dict[str, Any],
        *,
        responses_api: bool,
    ) -> None:
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature
        if self.config.reasoning_effort:
            if responses_api:
                payload["reasoning"] = {"effort": self.config.reasoning_effort}
            else:
                payload["reasoning_effort"] = self.config.reasoning_effort


class GroundedLlmAgent(BaseAnalysisAgent):
    agent_name = "grounded_llm"
    agent_version = "v1"

    def __init__(
        self,
        *,
        client: LlmClient,
        max_messages: int = 240,
        max_rendered_messages: int = 48,
        max_input_tokens: int = 12_000,
        max_output_tokens: int = 1_200,
        event_index: int = 0,
    ) -> None:
        _ensure_grounding_runtime_available()
        self.client = client
        self.max_messages = max_messages
        self.max_rendered_messages = max_rendered_messages
        self.max_input_tokens = max_input_tokens
        self.max_output_tokens = max_output_tokens
        self.event_index = event_index

    def prepare(self, materials: AnalysisMaterials) -> DenseSlicePlan:
        event_messages, source_label, source_start_iso, source_end_iso = (
            _select_source_pool(
                materials=materials,
                event_index=self.event_index,
            )
        )
        if not event_messages:
            raise RuntimeError("No messages are available for LLM analysis.")

        target_cap = min(self.max_messages, len(event_messages))
        selected = _densest_window(event_messages, target_cap)
        rendered = _select_representative_messages(
            selected,
            limit=min(self.max_rendered_messages, len(selected)),
        )
        trimmed = len(selected) < len(event_messages)
        estimated = _estimate_prompt_tokens(
            self._system_prompt(),
            self._user_prompt(
                materials=materials,
                messages=selected,
                rendered_messages=rendered,
            ),
        )

        while estimated > self.max_input_tokens and len(selected) > 48:
            target_cap = max(48, int(len(selected) * 0.85))
            selected = _densest_window(event_messages, target_cap)
            rendered = _select_representative_messages(
                selected,
                limit=min(self.max_rendered_messages, len(selected)),
            )
            trimmed = True
            estimated = _estimate_prompt_tokens(
                self._system_prompt(),
                self._user_prompt(
                    materials=materials,
                    messages=selected,
                    rendered_messages=rendered,
                ),
            )

        return DenseSlicePlan(
            source_label=source_label,
            source_start_iso=source_start_iso,
            source_end_iso=source_end_iso,
            source_message_count=len(event_messages),
            selected_messages=selected,
            selected_start_iso=selected[0].timestamp_iso,
            selected_end_iso=selected[-1].timestamp_iso,
            estimated_input_tokens=estimated,
            max_output_tokens=self.max_output_tokens,
            trimmed=trimmed,
            target_message_cap=len(selected),
            rendered_messages=rendered,
            rendered_message_count=len(rendered),
        )

    def analyze(
        self, materials: AnalysisMaterials, prepared: DenseSlicePlan
    ) -> AnalysisAgentOutput:
        bundle = self.client.analyze(
            system_prompt=self._system_prompt(),
            user_prompt=self._user_prompt(
                materials=materials,
                messages=prepared.selected_messages,
                rendered_messages=prepared.rendered_messages,
            ),
            max_output_tokens=prepared.max_output_tokens,
        )
        compact = bundle.parsed_payload or {"raw_text": bundle.raw_text}
        compact.update(
            {
                "model": getattr(self.client, "config", None).model
                if getattr(self.client, "config", None) is not None
                else "unknown",
                "slice": {
                    "source": prepared.source_label,
                    "source_s": prepared.source_start_iso,
                    "source_e": prepared.source_end_iso,
                    "source_n": prepared.source_message_count,
                    "sel_s": prepared.selected_start_iso,
                    "sel_e": prepared.selected_end_iso,
                    "sel_n": len(prepared.selected_messages),
                    "render_n": prepared.rendered_message_count,
                    "trimmed": prepared.trimmed,
                    "est_in": prepared.estimated_input_tokens,
                    "max_out": prepared.max_output_tokens,
                },
                "usage": {
                    "prompt": bundle.usage.prompt_tokens,
                    "completion": bundle.usage.completion_tokens,
                    "total": bundle.usage.total_tokens,
                    "reasoning": bundle.usage.reasoning_tokens,
                    "cached": bundle.usage.cached_tokens,
                },
                "finish_reason": bundle.finish_reason,
                "has_content": bool(bundle.raw_text),
                "reasoning_chars": len(bundle.reasoning_text),
            }
        )
        evidence = _build_evidence_from_payload(
            payload=bundle.parsed_payload,
            messages=prepared.selected_messages,
        )
        human_report = _render_human_report(
            parsed=bundle.parsed_payload,
            raw_text=bundle.raw_text,
            reasoning_text=bundle.reasoning_text,
            finish_reason=bundle.finish_reason,
            usage=bundle.usage,
            plan=prepared,
        )
        warnings: list[str] = []
        if not bundle.parsed_payload:
            warnings.append("LLM response was not valid JSON; raw text was preserved.")
        if not bundle.raw_text and bundle.finish_reason == "length":
            warnings.append(
                "DeepSeek returned no final content because max_tokens was exhausted by reasoning_content."
            )

        return AnalysisAgentOutput(
            agent_name=self.agent_name,
            agent_version=self.agent_version,
            human_report=human_report,
            compact_payload=compact,
            evidence=evidence,
            warnings=warnings,
        )

    def _system_prompt(self) -> str:
        return (
            "You analyze exported QQ chat records.\n"
            "Use only the provided chat slice.\n"
            "Allowed judgments: descriptive and behavioral only.\n"
            "Do not infer hidden motives.\n"
            "Return minified JSON only with keys:\n"
            "sm,tp,bh,pp,ev,nt,lim\n"
            "Where:\n"
            "- sm: short summary string\n"
            "- tp: list of main topics\n"
            "- bh: list of behavior/content pattern strings\n"
            "- pp: list of people objects {sid,role,why,e}\n"
            "- ev: list of evidence objects {id,why}\n"
            "- nt: list of open notes\n"
            "- lim: list of limitations or uncertainty notes\n"
            "Keep the JSON compact and grounded."
        )

    def _user_prompt(
        self,
        *,
        materials: AnalysisMaterials,
        messages: list[AnalysisMessageRecord],
        rendered_messages: list[AnalysisMessageRecord],
    ) -> str:
        top_tags = (
            ", ".join(
                f"{item.tag}:{item.count}" for item in materials.tag_summaries[:6]
            )
            or "none"
        )
        top_people = (
            ", ".join(
                f"{item.sender_id}:{item.message_count}"
                for item in materials.participant_profiles[:5]
            )
            or "none"
        )
        slice_stats = _summarize_slice(messages)
        lines = [
            f"Target={materials.target.display_name or materials.target.display_id}",
            f"Window={messages[0].timestamp_iso} -> {messages[-1].timestamp_iso}",
            f"SliceMessages={len(messages)}",
            f"RenderedMessages={len(rendered_messages)}",
            f"TagHints={top_tags}",
            f"PeopleHints={top_people}",
            f"SliceStats={slice_stats}",
            "Analyze what is mainly being talked about, what interaction patterns dominate, "
            "who are the key people inside this slice, and which evidence lines support that.",
            "Representative evidence lines from the slice:",
        ]
        for message in rendered_messages:
            lines.append(
                "mid={mid} | ts={ts} | sid={sid} | c={content}".format(
                    mid=message.message_uid,
                    ts=message.timestamp_iso,
                    sid=message.sender_id,
                    content=preview_text(
                        message.content.replace("\n", " / "),
                        180,
                    ),
                )
            )
        return "\n".join(lines)


def _select_source_pool(
    *,
    materials: AnalysisMaterials,
    event_index: int,
) -> tuple[list[AnalysisMessageRecord], str, str, str]:
    if materials.candidate_events and 0 <= event_index < len(
        materials.candidate_events
    ):
        event = materials.candidate_events[event_index]
        event_messages = [
            item
            for item in materials.messages
            if event.start_timestamp_ms <= item.timestamp_ms <= event.end_timestamp_ms
        ]
        if event_messages:
            return (
                event_messages,
                f"candidate_event_{event_index + 1}",
                event.start_timestamp_iso,
                event.end_timestamp_iso,
            )
    return (
        materials.messages,
        "chosen_time_window",
        materials.chosen_time_window.start_timestamp_iso,
        materials.chosen_time_window.end_timestamp_iso,
    )


def _densest_window(
    messages: list[AnalysisMessageRecord], target_size: int
) -> list[AnalysisMessageRecord]:
    if len(messages) <= target_size:
        return list(messages)
    best_start = 0
    best_duration = None
    for start in range(0, len(messages) - target_size + 1):
        end = start + target_size - 1
        duration = messages[end].timestamp_ms - messages[start].timestamp_ms
        if best_duration is None or duration < best_duration:
            best_duration = duration
            best_start = start
    return messages[best_start : best_start + target_size]


def _estimate_prompt_tokens(system_prompt: str, user_prompt: str) -> int:
    return _estimate_tokens(system_prompt) + _estimate_tokens(user_prompt) + 64


def _estimate_tokens(text: str) -> int:
    cjk = 0
    ascii_alnum = 0
    other = 0
    for char in text:
        if "\u4e00" <= char <= "\u9fff":
            cjk += 1
        elif char.isascii() and char.isalnum():
            ascii_alnum += 1
        else:
            other += 1
    estimate = int(cjk * 1.15 + ascii_alnum * 0.35 + other * 0.5)
    return max(estimate, len(text.split()))


def _summarize_slice(messages: list[AnalysisMessageRecord]) -> str:
    total = len(messages) or 1
    image_n = sum(1 for item in messages if item.features.image_count > 0)
    reply_n = sum(1 for item in messages if item.features.has_reply)
    low_n = sum(1 for item in messages if item.features.low_information)
    senders = len({item.sender_id for item in messages})
    return (
        f"msg_n={len(messages)},sender_n={senders},"
        f"image_r={image_n / total:.2f},reply_r={reply_n / total:.2f},low_r={low_n / total:.2f}"
    )


def _select_representative_messages(
    messages: list[AnalysisMessageRecord], *, limit: int
) -> list[AnalysisMessageRecord]:
    if len(messages) <= limit:
        return list(messages)
    ranked: list[tuple[float, int, AnalysisMessageRecord]] = []
    for index, message in enumerate(messages):
        score = 0.0
        score += len(message.text_content or message.content) * 0.02
        score += float(len(message.features.message_tags) * 3)
        score += float(message.features.image_count * 2)
        score += float(message.features.has_reply) * 2
        score += float(message.features.has_forward) * 4
        score += float(message.features.repeated_noise) * 2
        if message.text_content and len(message.text_content.strip()) >= 8:
            score += 1.5
        ranked.append((score, index, message))
    chosen = sorted(ranked, key=lambda item: (item[0], -item[1]), reverse=True)[:limit]
    ordered = sorted(chosen, key=lambda item: item[1])
    return [item[2] for item in ordered]


def _extract_usage(body: dict[str, Any]) -> LlmUsageSnapshot:
    usage = body.get("usage", {})
    completion_details = usage.get("completion_tokens_details", {}) or {}
    prompt_details = usage.get("prompt_tokens_details", {}) or {}
    return LlmUsageSnapshot(
        prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
        completion_tokens=int(usage.get("completion_tokens", 0) or 0),
        total_tokens=int(usage.get("total_tokens", 0) or 0),
        reasoning_tokens=int(
            completion_details.get("reasoning_tokens", 0)
            or usage.get("reasoning_tokens", 0)
            or 0
        ),
        cached_tokens=int(prompt_details.get("cached_tokens", 0) or 0),
    )


def _ensure_grounding_runtime_available() -> None:
    if _GROUNDING_IMPORT_ERROR is None:
        return
    raise RuntimeError(
        "Grounded LLM analysis runtime is unavailable because dependent analysis modules "
        f"failed to import: {_GROUNDING_IMPORT_ERROR}"
    ) from _GROUNDING_IMPORT_ERROR


def _build_openai_input_image(image: MultimodalInputImage) -> dict[str, Any]:
    resolved_path = image.path.expanduser().resolve()
    if not resolved_path.exists():
        raise FileNotFoundError(f"Multimodal image does not exist: {resolved_path}")
    mime_type = image.mime_type
    if not mime_type:
        guessed, _ = mimetypes.guess_type(str(resolved_path))
        mime_type = guessed or "image/jpeg"
    encoded = base64.b64encode(resolved_path.read_bytes()).decode("ascii")
    return {
        "type": "input_image",
        "image_url": f"data:{mime_type};base64,{encoded}",
    }


def _build_openai_chat_text_payload(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int,
    temperature: float | None,
    reasoning_effort: str | None,
    stream: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_output_tokens,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    if stream:
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
    return payload


def _build_openai_chat_multimodal_payload(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    images: Iterable[MultimodalInputImage],
    max_output_tokens: int,
    temperature: float | None,
    reasoning_effort: str | None,
    stream: bool = False,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    if user_prompt.strip():
        content.append({"type": "text", "text": user_prompt.strip()})
    for index, image in enumerate(images, start=1):
        if image.label:
            content.append({"type": "text", "text": f"[image {index} label] {image.label.strip()}"})
        response_item = _build_openai_input_image(image)
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": response_item["image_url"]},
            }
        )
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        "max_tokens": max_output_tokens,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    if stream:
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
    return payload


def _should_fallback_to_chat_completions(exc: httpx.HTTPStatusError) -> bool:
    response = exc.response
    request = exc.request
    return (
        response is not None
        and request is not None
        and response.status_code in {404, 405}
        and str(request.url).rstrip("/").endswith("/responses")
    )


def _extract_chat_completion_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
        return "\n".join(parts).strip()
    return ""


def _extract_chat_completion_reasoning(message: dict[str, Any]) -> str:
    for key in ("reasoning_content", "reasoning", "reasoning_text"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_openai_output_text(body: dict[str, Any]) -> str:
    direct = body.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    chunks: list[str] = []
    for item in body.get("output", []) or []:
        for content in item.get("content", []) or []:
            if content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str) and text:
                    chunks.append(text)
    return "\n".join(chunk.strip() for chunk in chunks if chunk.strip()).strip()


def _extract_openai_usage(body: dict[str, Any]) -> LlmUsageSnapshot:
    usage = body.get("usage", {}) or {}
    input_details = usage.get("input_tokens_details", {}) or {}
    output_details = usage.get("output_tokens_details", {}) or {}
    prompt_tokens = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
    completion_tokens = int(
        usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
    )
    total_tokens = int(
        usage.get("total_tokens", prompt_tokens + completion_tokens) or 0
    )
    return LlmUsageSnapshot(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        reasoning_tokens=int(output_details.get("reasoning_tokens", 0) or 0),
        cached_tokens=int(input_details.get("cached_tokens", 0) or 0),
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    if start < 0:
        return {}
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    return {}
    return {}


def _build_evidence_from_payload(
    *,
    payload: dict[str, Any],
    messages: list[AnalysisMessageRecord],
) -> list[AnalysisEvidenceItem]:
    if not payload:
        return []
    message_map = {item.message_uid: item for item in messages}
    evidence: list[AnalysisEvidenceItem] = []
    for item in payload.get("ev", []):
        message_uid = str(item.get("id", "")).strip()
        if not message_uid:
            continue
        message = message_map.get(message_uid)
        if message is None:
            continue
        evidence.append(
            AnalysisEvidenceItem(
                message_uid=message.message_uid,
                timestamp_iso=message.timestamp_iso,
                sender_id=message.sender_id,
                sender_name=message.sender_name,
                content=preview_text(message.content, 100),
                reason=str(item.get("why", "")).strip() or "llm-evidence",
                tags=[],
            )
        )
    return evidence


def _render_human_report(
    *,
    parsed: dict[str, Any],
    raw_text: str,
    reasoning_text: str,
    finish_reason: str,
    usage: LlmUsageSnapshot,
    plan: DenseSlicePlan,
) -> str:
    lines = [
        "## Grounded LLM Analysis",
        f"- 选片来源: {plan.source_label}",
        f"- 原始片段: {plan.source_start_iso} -> {plan.source_end_iso} | {plan.source_message_count} 条",
        f"- 实际切片: {plan.selected_start_iso} -> {plan.selected_end_iso} | {len(plan.selected_messages)} 条",
        f"- 送模证据行: {plan.rendered_message_count} 条",
        f"- 预算: estimated_input_tokens={plan.estimated_input_tokens} | max_output_tokens={plan.max_output_tokens}",
        (
            "- 实际用量: prompt={p} | completion={c} | total={t} | reasoning={r} | cached={k}".format(
                p=usage.prompt_tokens,
                c=usage.completion_tokens,
                t=usage.total_tokens,
                r=usage.reasoning_tokens,
                k=usage.cached_tokens,
            )
        ),
        f"- finish_reason: {finish_reason or 'unknown'}",
    ]
    if parsed:
        if parsed.get("sm"):
            lines.append(f"- 摘要: {parsed['sm']}")
        topics = parsed.get("tp", [])
        if topics:
            lines.append("- 主题: " + " / ".join(str(item) for item in topics))
        behaviors = parsed.get("bh", [])
        if behaviors:
            lines.append("- 行为模式: " + " / ".join(str(item) for item in behaviors))
        people = parsed.get("pp", [])
        if people:
            lines.append("- 重点人物:")
            for item in people[:5]:
                evidence = ",".join(str(ev) for ev in item.get("e", [])[:3])
                lines.append(
                    "  - {sid} | {role} | {why} | e={evi}".format(
                        sid=item.get("sid", ""),
                        role=item.get("role", ""),
                        why=item.get("why", ""),
                        evi=evidence or "none",
                    )
                )
        notes = parsed.get("nt", [])
        if notes:
            lines.append("- 备注: " + "；".join(str(item) for item in notes))
        limits = parsed.get("lim", [])
        if limits:
            lines.append("- 限制: " + "；".join(str(item) for item in limits))
    else:
        lines.append("- 原始输出:")
        lines.append(raw_text)
        if not raw_text and finish_reason == "length":
            lines.append(
                f"- 说明: DeepSeek 返回了 {len(reasoning_text)} 字符的 reasoning_content，但最终 content 为空。"
            )
    return "\n".join(lines)
