# Chat Orchestrator Lifecycle Engine 实现规范

## 目标

本文件定义 `lifecycle.py` 的 turn loop。它负责把 context、model、tools、hooks 串成一个可复用的 engine，而不是把流程写进 CLI 或单个 mission profile。

推荐实现落点：

```text
src/qq_data_core/chat_orchestrator/
  lifecycle.py
  hooks.py
  transitions.py
```

## Claude Code 对照基线

本地 Claude Code 源码路径：

- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/QueryEngine.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/query.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/query/config.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/query/deps.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/query/stopHooks.ts`

本地 CC 解析文档：

- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/architecture_overview.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/planning_execution_permissions.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/function_index.md`

## Engine 形状

生命周期引擎必须是显式状态机，不要用“一个大函数 + 一堆 if/else”。

推荐状态：

```python
class TurnStage(StrEnum):
    PREPARE = "prepare"
    BUILD_CONTEXT = "build_context"
    CALL_MODEL = "call_model"
    EXECUTE_TOOLS = "execute_tools"
    POST_TOOLS = "post_tools"
    FINALIZE = "finalize"
    FAILED = "failed"
```

推荐对象：

```python
@dataclass(slots=True)
class TurnState:
    session_id: str
    turn_id: str
    iteration: int
    stage: TurnStage
    messages: list[RuntimeMessage]
    pending_tool_calls: list[ToolCall]
    compacted: bool
    failure_reason: str | None


class LifecycleEngine:
    async def run_turn(
        self,
        request: OrchestratorRequest,
        session_state: SessionState,
    ) -> OrchestratorTurnResult: ...
```

## v1 turn loop

v1 统一按下面的 loop 形状实现：

```python
while True:
    packet = context_runtime.build_turn_packet(...)
    model_response = await model_client.query(packet, ...)
    if not model_response.tool_calls:
        return finalize(...)
    tool_result = await tool_executor.execute(...)
    turn_state = apply_tool_result(turn_state, tool_result)
```

必须显式限制：

- `max_iterations_per_turn`
- `max_tool_calls_per_turn`
- `max_consecutive_failures`

否则一个坏的 tool schema 或坏的 prompt 会把整个 session 卡死。

## hooks 插点

v1 只保留四类 hook：

1. `before_model_call`
2. `after_model_response`
3. `after_tool_batch`
4. `after_turn`

hook 的输入必须是结构化对象，不能直接把整个 engine 实例透传给 hook。

```python
class LifecycleHook(Protocol):
    async def __call__(self, event: LifecycleEvent) -> None: ...
```

## deps 注入

像 Claude Code 的 `query/deps.ts` 一样，engine 需要窄依赖注入面，至少把这几项抽成 `LifecycleDeps`：

- `model_client`
- `tool_executor`
- `context_runtime`
- `analytics_sink`
- `clock`
- `id_factory`

这样测试时可以直接假造 model/tool 行为，而不是 monkeypatch 整个模块图。

## 失败与终止语义

v1 至少要区分下面几种结束原因：

- `completed`
- `tool_limit_reached`
- `blocked_by_policy`
- `model_error`
- `tool_error`
- `hook_error`

不要只返回一个 `"failed"`。否则上层没法判断是重试、降级还是直接报错。

## 状态持久化顺序

每轮 turn 的持久化顺序固定：

1. 先落原始 `RuntimeMessage`
2. 再落 `TurnState` 摘要
3. 再落 `AnalyticsEvent`
4. 最后落大结果 artifact 路径

不要先写 artifact 路径、后写消息主体。否则恢复 session 时会出现“有工具结果文件，但 transcript 里没有对应调用”的坏状态。

## 直接复用什么

- 复用 `QueryEngine.ts` 的“一个 engine 拥有一整个 conversation 生命周期”
- 复用 `query.ts` 的 loop 轮廓
- 复用 `query/config.ts` 的“每轮 query 入口先快照 immutable config”
- 复用 `query/deps.ts` 的窄依赖注入方式
- 复用 `query/stopHooks.ts` 的“post-turn hook 是 engine 级设施，不属于单个 tool”

## 必须改写什么

- Claude Code 的 loop 混有 REPL、slash command、streaming UI 细节
  - 本项目必须把 UI 细节完全剥离
- Claude Code 的 stop hooks 很多围绕 coding workflow
  - 本项目要改成导出、分析、media 恢复、审计的域内 hook
- Claude Code 的 tool result pairing 要处理复杂 thinking/tool_use 轨迹
  - 本项目 v1 只处理清晰的 tool call/result 关联，不先引入复杂 thinking 兼容层

## 当前 v1 实现什么

v1 只实现：

- 单 engine 的单轮 loop
- model -> tools -> model 的基本往返
- hook 四插点
- 可区分的终止原因
- 窄依赖注入
- 可恢复的 turn-level state 持久化

v1 不实现：

- streaming fallback
- reactive compact recovery
- 多 worker 协调 loop
- mid-turn session migration

## 后续再实现什么

后续再加：

- 真正的 streaming tool execution
- tool batch 中断与恢复
- coordinator / worker 双层 turn loop
- session resume 后的 mode 对齐
- model fallback 和 compact retry 梯度

## 实现约束

1. `LifecycleEngine` 只能消费接口，不能直接 import NapCat provider 细节。
2. 所有阶段转换都必须写入 `TurnStage`，不要靠日志推断。
3. engine 的输出必须能被 CLI、GUI、analyzer 直接消费，不能夹带 REPL UI 组件。
