# Chat Orchestrator Analytics Runtime 实现规范

## 目标

本文件定义 orchestrator 的 analytics runtime，重点不是埋点数量，而是：

- 事件入口统一
- sink 可替换
- metadata 安全
- context/tool/model 的关键运行指标能被稳定记录

推荐实现落点：

```text
src/qq_data_core/chat_orchestrator/
  analytics.py
  analytics_types.py
```

## Claude Code 对照基线

本地 Claude Code 源码路径：

- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/services/analytics/index.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/services/analytics/config.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/services/analytics/metadata.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/utils/contextAnalysis.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/bootstrap/state.ts`

本地 CC 解析文档：

- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/architecture_overview.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/context_and_compaction.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/file_index.md`

## 统一事件入口

v1 必须提供单一入口：

```python
class AnalyticsCollector:
    def log(self, event_name: str, metadata: AnalyticsMetadata) -> None: ...
    async def flush(self) -> None: ...
```

任何模块都不能自己打开文件直接写 analytics 行。都先过 `AnalyticsCollector`。

## sink 结构

v1 只做两种 sink：

1. `jsonl_file_sink`
   - `state/chat_orchestrator/analytics/<date>.jsonl`
2. `null_sink`
   - 测试或显式关闭 telemetry 时使用

collector 初始化之前的事件允许先入队，sink attach 后统一刷出。这个行为直接沿用 Claude Code `analytics/index.ts` 的设计。

## metadata 最小结构

```python
@dataclass(slots=True)
class AnalyticsMetadata:
    session_id: str
    turn_id: str | None
    mission_profile: str
    runtime_mode: str
    model_name: str | None
    duration_ms: int | None
    numeric: dict[str, int | float]
    flags: dict[str, bool]
```

`numeric` 和 `flags` 之外，v1 不允许自由文本字段泛滥。

## v1 必记事件

v1 只保留下列核心事件：

- `orchestrator_session_started`
- `orchestrator_turn_started`
- `orchestrator_context_built`
- `orchestrator_compact_applied`
- `orchestrator_model_called`
- `orchestrator_tool_completed`
- `orchestrator_turn_completed`
- `orchestrator_turn_failed`

不要一上来把每个小函数都变成事件。

## v1 必记指标

至少记录这些数字：

- `context_input_tokens`
- `context_reserved_output_tokens`
- `stable_prefix_tokens`
- `message_evidence_tokens`
- `tool_result_tokens`
- `compacted_tokens_freed`
- `tool_duration_ms`
- `model_duration_ms`
- `assets_copied`
- `assets_missing`

对 chat/export 场景，`assets_missing` 和 `assets_copied` 是一等指标，不是后处理统计。

## 安全规则

本仓库的 analytics 不能照搬 Claude Code 的元数据内容，因为我们的数据更敏感。v1 必须遵守：

- 不记录原始消息正文
- 不记录完整本地路径
- 不记录明文 QQ ID
- 需要标识聊天对象时，只记 hash 或 scope class

可以记录：

- `chat_scope=group|private`
- `tool_name`
- `profile_id`
- `mode_id`
- 数值型 token 与时延

## source-level context stats

像 Claude Code `contextAnalysis.ts` 一样，context 成本必须按 source class 记录，而不是只记总 token。

至少要分：

- `stable_prefix`
- `objective`
- `direct_message_evidence`
- `relation_context`
- `tool_results`
- `compact_summary`

这部分由 context runtime 产出，analytics 只负责写出。

## 直接复用什么

- 复用 `analytics/index.ts` 的“先 collect，后 attach sink”的入口模型
- 复用 `analytics/config.ts` 的“统一开关判断”
- 复用 `analytics/metadata.ts` 的“metadata 必须有安全边界”原则
- 复用 `contextAnalysis.ts` 的“按 source class 计 token”
- 复用 `bootstrap/state.ts` 的“session 级指标集中保管”思路

## 必须改写什么

- Claude Code 的 analytics 会涉及模型、工具、代码路径、MCP 名称
  - 本项目要改成更严格的隐私规则
- Claude Code 的 metadata 有不少产品分发字段
  - 本项目 v1 只保留运行时诊断字段，不做产品运营字段
- Claude Code 的 sink 设计为 Datadog/1P 兼容
  - 本项目 v1 只做本地 JSONL sink

## 当前 v1 实现什么

v1 只实现：

- 单入口 collector
- attachable sink
- 本地 JSONL sink
- 核心事件 8 个
- source-level context stats
- tool/model/asset 三类关键数值

v1 不实现：

- 远端遥测上传
- trace/span 体系
- PII 分级多路由
- 实时 dashboard

## 后续再实现什么

后续再加：

- OpenTelemetry / metrics backend
- profile-aware benchmark 统计
- 误判审计与人工回标闭环指标
- GUI 实时运行面板

## 实现约束

1. analytics sink 失败不能拖垮主流程，只能降级。
2. 所有 string metadata 必须先过安全审查函数。
3. context token 分布必须来自 runtime 真值，不允许 sink 端猜测。
