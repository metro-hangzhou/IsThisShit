# Chat Orchestrator Runtime 总览实现规范

## 目标

本文件定义 `chat_orchestrator` 的运行时骨架，目标不是讲阶段路线，而是把 v1 该落成哪些 Python 模块、模块边界如何切、每一轮 turn 如何流转写清楚。

推荐实现落点：

```text
src/qq_data_core/chat_orchestrator/
  runtime.py
  state.py
  lifecycle.py
  context.py
  modes.py
  mission_profiles.py
  analytics.py
  hooks.py
  tools/
    base.py
    registry.py
    executor.py
```

## Claude Code 对照基线

本地 Claude Code 源码路径：

- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/QueryEngine.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/query.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/bootstrap/state.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/context.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/utils/queryContext.ts`

本地 CC 解析文档：

- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/architecture_overview.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/file_index.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/function_index.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/migration_notes_for_shi_analyzer.md`

## 核心实现结论

Claude Code 的真正可搬运点不是 UI，而是三层拆分：

1. `runtime facade`
   - 接请求
   - 组配置
   - 保存长生命周期 state
2. `lifecycle engine`
   - 跑 turn loop
   - 驱动模型调用、工具调用、post hooks
3. `context runtime`
   - 只负责稳定前缀、动态 packet、compact 与预算

在本仓库里，`ChatOrchestratorRuntime` 必须是单一入口，不能把以下逻辑散落在 CLI、NapCat provider、analysis pack 生成器里：

- mission profile 解析
- mode 解析
- tool registry 装配
- context packet 构建
- analytics 生命周期
- turn state 持久化

## 运行时对象

建议直接定义以下对象：

```python
@dataclass(slots=True)
class OrchestratorRequest:
    session_id: str
    mission_profile: str
    mode: str
    user_input: str | None
    incoming_messages: list[NormalizedMessage]
    options: RuntimeOptions


@dataclass(slots=True)
class OrchestratorTurnResult:
    session_id: str
    turn_id: str
    output_messages: list[RuntimeMessage]
    tool_artifacts: list[RuntimeArtifact]
    analytics_events: list[AnalyticsEvent]
    next_state: "SessionState"


class ChatOrchestratorRuntime:
    async def run_turn(
        self,
        request: OrchestratorRequest,
    ) -> OrchestratorTurnResult: ...
```

`runtime.py` 只做装配，不写业务分支。真正流程由 `lifecycle.py` 驱动。

## v1 主流程

v1 统一按下面顺序执行：

1. `runtime.py`
   - 读取 `MissionProfile`
   - 解析 `RuntimeMode`
   - 创建或恢复 `SessionState`
2. `context.py`
   - 生成稳定前缀
   - 生成 turn packet
3. `lifecycle.py`
   - 调模型
   - 解析 tool calls
   - 执行工具
   - 合并 tool results
   - 生成最终 assistant output
4. `analytics.py`
   - 记录 turn 级事件
5. `state.py`
   - 持久化 session state

这里必须保持一个约束：CLI 只是入口，不拥有 orchestrator 状态机。GUI 或 analyzer 直调时也必须走同一条 runtime。

## SessionState 最小字段

`state.py` 在 v1 至少要保存：

```python
@dataclass(slots=True)
class SessionState:
    session_id: str
    mission_profile: str
    mode: str
    turn_index: int
    messages: list[RuntimeMessage]
    stable_prefix_cache_key: str | None
    compact_summary: str | None
    invoked_tools: list[str]
    token_stats: TokenStats
    pending_flags: dict[str, bool]
```

`messages` 保存运行时 transcript，`compact_summary` 保存已压缩状态，`pending_flags` 用来表达“下一轮需要做的恢复动作”，不要把这些 flag 散在 CLI 或 tool executor 内部。

## 直接复用什么

直接复用的是 Claude Code 的结构，不是 TypeScript 代码本身：

- 复用 `QueryEngine.ts` 的单入口生命周期模型
  - 一轮 turn 的所有副作用都挂在 engine 上
- 复用 `query.ts` 的 loop 形状
  - `prepare -> maybe compact -> model -> tools -> post hooks -> persist`
- 复用 `bootstrap/state.ts` 的显式 session state 思路
  - 长生命周期字段统一归口
- 复用 `context.ts` 与 `utils/queryContext.ts` 的稳定前缀拆分
  - 稳定上下文与动态 turn context 不混写

## 必须改写什么

这些地方不能直接照搬：

- Claude Code 的 transcript 语义是 `human / assistant / tool`
  - 本项目必须改成 `chat message / orchestrator message / tool message / artifact`
- Claude Code 的权限模型面向 Bash/Read/Edit
  - 本项目必须改成 NapCat 公共接口、导出写盘、分析工具的域内权限
- Claude Code 的 UI 触发是 REPL / slash commands
  - 本项目必须改成 CLI/API/GUI 共用的纯 runtime 入口
- Claude Code 的 compaction 面向编码会话
  - 本项目必须改成面向消息图、media artifact、analysis pack 的 compact

## 当前 v1 实现什么

v1 只实现以下范围：

- 单进程、单主引擎的 orchestrator runtime
- 明确的 `SessionState` 与 `TurnResult`
- 稳定前缀 + turn packet 的双层 context
- 单轮 tool loop
- 本地 JSONL 级 analytics sink
- mission profile 装配
- headless 与 interactive 共用同一 runtime

v1 不实现：

- 多 worker 并行协调
- 跨进程 session resume
- 背景 session memory 抽取
- 远端 session server

## 后续再实现什么

后续版本再加：

- `coordinator / worker` 双层 runtime
- forked subagent 或异步 worker backend
- session memory 后台提取与优先 compact
- 可恢复的 long-running task
- GUI 直连 runtime 的事件流接口

## 实现约束

为了不把 runtime 再次做成“大杂烩”，必须坚持下面三条：

1. `runtime.py` 不写业务规则，只做装配。
2. `lifecycle.py` 不拼 prompt 原文，只消费 `ContextPacket`。
3. `tools/` 不直接改 session 全局状态，只返回结构化 `ContextPatch` 或 `Artifact`。
