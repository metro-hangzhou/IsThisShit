# Chat Orchestrator Tool Runtime 实现规范

## 目标

本文件定义 orchestrator 的 tool runtime，包括：

- tool 协议
- registry
- executor
- 大结果持久化
- 并发分组规则

推荐实现落点：

```text
src/qq_data_core/chat_orchestrator/tools/
  base.py
  registry.py
  executor.py
  persistence.py
```

## Claude Code 对照基线

本地 Claude Code 源码路径：

- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/Tool.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/services/tools/toolOrchestration.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/services/tools/StreamingToolExecutor.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/utils/toolResultStorage.ts`

本地 CC 解析文档：

- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/file_index.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/function_index.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/architecture_overview.md`

## 工具协议

v1 工具协议必须是显式 schema，不接受“随便塞 dict”。

```python
class OrchestratorTool(Protocol):
    name: str
    concurrency: Literal["serial", "read_only_batch"]
    mutates_state: bool

    def validate(self, payload: dict) -> ToolPayload: ...

    async def invoke(
        self,
        payload: ToolPayload,
        context: ToolRuntimeContext,
    ) -> ToolInvocationResult: ...
```

`ToolInvocationResult` 至少要返回：

- `messages`
- `artifacts`
- `context_patch`
- `metrics`

## registry

推荐最小接口：

```python
class ToolRegistry:
    def register(self, tool: OrchestratorTool) -> None: ...
    def resolve(self, name: str) -> OrchestratorTool: ...
    def list_allowed(self, mission_profile: str, mode: str) -> list[str]: ...
```

registry 负责装配，不负责执行。

## executor

executor 负责三件事：

1. 校验 schema
2. 判定并发分组
3. 执行并把结果回填为 `RuntimeMessage`

并发分组规则直接照着 Claude Code 的 `partitionToolCalls` 结构实现：

- 连续的 `read_only_batch` 可以并发
- 任意 `serial` 工具必须独占

这样可以保住 v1 的正确性，同时不把 executor 写成全串行。

## 大结果持久化

像 Claude Code 的 `toolResultStorage.ts` 一样，大结果不能直接一直留在 prompt 里。

推荐落点：

- `state/chat_orchestrator/tool-results/<session_id>/<tool_call_id>.json`

prompt 中只回填：

- 结果摘要
- 持久化路径
- 必要的 preview

## v1 内建工具

v1 内建工具建议只保留与本仓库目标直接相关的几个：

1. `napcat_history_fetch`
   - 只调用公开历史接口或已批准 fast plugin 路线
2. `napcat_metadata_fetch`
   - 只调用公开 metadata 接口
3. `napcat_media_hydrate`
   - 走正式 NapCat-only 媒体恢复路线
4. `export_bundle_write`
   - 写 JSONL/TXT + assets + manifest
5. `analysis_pack_read`
   - 读取本地 analysis pack / manifest / benchmark 结果

这里必须遵守仓库 AGENTS 约束：

- 不依赖 NapCat 内部 TypeScript 模块
- 正式导出只走公共接口与批准的 fast plugin 路线

## tool runtime context

`ToolRuntimeContext` 最少要提供：

```python
@dataclass(slots=True)
class ToolRuntimeContext:
    session_state: SessionState
    mission_profile: MissionProfile
    runtime_mode: RuntimeModeSpec
    analytics: AnalyticsCollector
    cancellation: CancellationToken
```

工具不能直接拿整个 `ChatOrchestratorRuntime`，否则会重新形成大耦合。

## 直接复用什么

- 复用 `Tool.ts` 的“工具是显式协议对象”
- 复用 `toolOrchestration.ts` 的“先分批，再执行”的 executor 结构
- 复用 `StreamingToolExecutor.ts` 的“并发安全工具并行，不安全工具独占”原则
- 复用 `toolResultStorage.ts` 的“大结果落盘，prompt 只留摘要和路径”

## 必须改写什么

- Claude Code 的工具主要围绕文件、命令、MCP
  - 本项目工具必须换成 NapCat 公共接口、导出写盘、分析读写
- Claude Code 的 tool result 消息格式服务于 Anthropic tool_use/tool_result
  - 本项目要改成通用 runtime message，不把模型厂商协议写死进核心层
- Claude Code 的中断模型围绕 Bash 进程
  - 本项目 v1 只做简单 cancellation，不先复制复杂 sibling abort 语义

## 当前 v1 实现什么

v1 只实现：

- 显式 tool 协议
- registry + executor
- 两级并发规则
- 大结果落盘
- 与 NapCat 公共接口对齐的内建工具集

v1 不实现：

- MCP tool bridge
- worker-to-worker tool forwarding
- 真正的流式 progress multiplexing
- 动态 marketplace tool 安装

## 后续再实现什么

后续再加：

- 长任务进度流
- GUI 可订阅的 tool progress 事件
- 外部插件型工具提供者
- worker 级工具隔离和能力降级

## 实现约束

1. tool runtime 必须只依赖抽象 context，不依赖 CLI。
2. tool schema 校验失败要返回结构化错误，不要 silently coerce。
3. tool result 落盘后，prompt 内必须只回填稳定摘要与路径，不重复塞全文。
