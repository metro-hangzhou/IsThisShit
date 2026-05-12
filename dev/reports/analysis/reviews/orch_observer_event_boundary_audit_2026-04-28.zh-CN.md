# ORCH Observer 事件边界审计

日期：2026-04-28

## 背景

LLM Sessions / ORCH Observer 的目标不是把后端所有调试字段倾倒到前端，而是让人类能按 ORCH 的真实执行顺序观察：

- 用户投递了什么审阅目标和 QQ 原文。
- ORCH 如何整理审阅材料。
- ORCH 为什么调用工具、工具拿回了什么证据。
- 模型拿到了什么审阅指令。
- 模型实时输出了什么。
- 最终审阅报告是否可被人类复核。

本轮人工验收发现，Observer 页面出现了多处“看似 UI 问题，实为事件边界问题”的现象：

- 同一次模型提示词被显示两次。
- 工具结果存在 `loop.tool_observation` 与 `tool.completed` 双份语义。
- worker / agent 内部字段直接出现在 ORCH 外部观察界面。
- runtime phase 可能被原始事件名污染，导致前端状态语义不稳定。

## 根因

旧链路为：

```text
llm_session_service
  -> ChatOrchestratorEngine(request.event_callback=emit)
  -> MissionRegistry.worker_factory(request)
  -> ShiAnalysisMissionWorker(event_callback=request.event_callback)
  -> BenshiMasterLlmAgent(event_callback=request.event_callback)
```

这意味着 `BenshiMasterLlmAgent` 的内部实现事件会直接写进外部 session event log。典型泄漏事件包括：

- `llm.prompt_built`
- `prompt.built`
- `session.stream_chunk`
- `llm.response_completed`

同时 ORCH engine 自身还会为同一工具结果写：

- `loop.tool_observation`
- `tool.completed`

以及为同一失败写：

- `loop.tool_failure`
- `tool.failed`

这些事件在工程内部有调试价值，但不能作为 Observer 的产品级主线事件直接透出。

## 修复原则

1. ORCH 是对外 observer event stream 的唯一 owner。
2. worker / agent 可以产生私有事件，但必须经 ORCH 边界适配。
3. 新 session 只写 canonical public event。
4. 旧 session 通过读取层兼容，不通过继续发旧事件来兼容。
5. UI 主线只展示人类可理解的行为，不展示内部事件名、函数名、裸字段名。
6. Raw/Inspect 可以保留排障入口，但不能抢占主线阅读。

## 本轮代码落点

- `src/qq_data_analysis/orch/engine.py`
  - 新增 `_WorkerEventBoundary`。
  - ORCH 创建 worker 时传入的是边界适配器，不再传裸 `request.event_callback`。
  - worker-private `llm.prompt_built` / `prompt.built` 被合并为单一公开 `llm.prompt_built`。
  - worker-private `session.stream_chunk` 被转为公开 `session.stream_chunk`，并继续转发给可选 `llm_stream_callback`。
  - worker-private `llm.response_completed` 被转为单一公开 `llm.response_completed`。
  - ORCH 不再写 `loop.tool_observation` 和 `loop.tool_failure`，只写 `tool.completed` / `tool.failed`。

- `src/qq_data_analysis/benshi_llm_agent.py`
  - 删除新写入 `prompt.built`。
  - 低层 agent 保留 `llm.prompt_built`、`session.stream_chunk`、`llm.response_completed` 作为 agent 内部可适配事件。

- `src/qq_data_analysis/llm_session_service.py`
  - 新增 `_canonical_frontend_events()`，读取旧 session 时过滤：
    - `llm.stream_chunk`
    - 已有 canonical prompt 时的 `prompt.built`
    - 已有 `tool.completed` 时的同 payload `loop.tool_observation`
    - 已有 `tool.failed` 时的同 payload `loop.tool_failure`
  - `prompt.built` 与 `llm.prompt_built` 的兼容不是“先到先用”：只要同一旧 session 中存在 canonical `llm.prompt_built`，主线就必须丢弃旧 `prompt.built`，即使旧事件在文件顺序上更早。
  - 新增 `_runtime_phase_for_event()`，避免 runtime phase 被原始事件名污染。
  - mock session 改为使用 canonical `llm.prompt_built`。

## 二次观测：仍需防止的架构泄漏模式

本轮看到的重复 prompt/tool 只是同类问题中最容易被 UI 放大的一个例子。后续开发需要按以下边界判断是否合规：

- 内层 worker/agent 的字段只能在 ORCH 内部接口或 Raw/Inspect 中流动，不能默认成为 Observer 主线。
- `compact_payload` 内的历史 alias 字段只能作为兼容输入，例如 `shi_component_analysis_layer` / `shi_component_analysis`、`crowd_reaction_items` / `reaction_patterns`；前端主报告必须优先消费 `final_review` / `finalReportViewModel`。
- 工具调用主线必须以 ORCH 公共工具事件为准：`tool.requested`、`tool.completed`、`tool.failed`。`loop.*` 只能作为内部 trace 或旧 session 兼容材料。
- 事件状态必须来自稳定 phase 映射，不能让任意内部 `event_type` 进入 `runtime.phase` 后再扩散到 registry/UI。
- 新增 mission worker 时，禁止把裸 `request.event_callback` 继续向低层透传；必须经过 ORCH 边界适配器或一个同等职责的 adapter。

## 仍需后续关注

- `AnalysisAgentOutput.compact_payload` 仍包含若干历史 alias 字段，例如 `shi_component_analysis_layer` / `shi_component_analysis`、`crowd_reaction_items` / `reaction_patterns`。这些属于结果 payload 兼容层，不应直接作为主线 UI 渲染来源。
- 前端仍应以 `final_review` / `finalReportViewModel` 为审阅报告主数据源。
- Raw/Inspect 中可以保留 legacy/debug payload，但需要明确标注为调试信息。

## 验收标准

新 ORCH live run 应满足：

- event log 中不再出现新写入的 `prompt.built`。
- event log 中不再出现新写入的 `loop.tool_observation` / `loop.tool_failure`。
- prompt 主线只出现一次。
- tool result 主线只出现一次。
- token 流仍通过 `session.stream_chunk` 实时到达。
- 旧 session 仍可离线打开，且主线不会重复渲染 legacy alias。
