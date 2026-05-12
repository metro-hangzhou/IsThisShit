# Chat Orchestrator Future Extension Surface 实现规范

## 目标

本文件定义未来扩展面，但仍然按“如何实现”来写：哪些接口从 v1 就要预留，哪些内部实现故意不开放，避免后续加 GUI、analyzer、benchmark、worker 时重写核心 runtime。

推荐实现落点：

```text
src/qq_data_core/chat_orchestrator/
  interfaces.py
  hooks.py
  plugins.py
```

## Claude Code 对照基线

本地 Claude Code 源码路径：

- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/query/deps.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/Tool.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/query/stopHooks.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/QueryEngine.ts`

本地 CC 解析文档：

- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/file_index.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/function_index.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/architecture_overview.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/migration_notes_for_shi_analyzer.md`

## v1 就要预留的扩展接口

v1 必须显式预留下面这些协议：

```python
class ModelClient(Protocol): ...
class ContextRuntime(Protocol): ...
class ToolRegistry(Protocol): ...
class ToolExecutor(Protocol): ...
class AnalyticsSink(Protocol): ...
class SessionStateStore(Protocol): ...
class MissionProfileProvider(Protocol): ...
class LifecycleHook(Protocol): ...
```

这些接口都应该收在 `interfaces.py`，不要分散在各实现文件顶部各写各的。

## 哪些面是稳定 surface

v1 可以承诺稳定的只有这些：

- `OrchestratorRequest`
- `OrchestratorTurnResult`
- `MissionProfile`
- `RuntimeModeSpec`
- `ContextPacket`
- `ToolInvocationResult`
- `AnalyticsEvent`
- 上面列出的 protocol

这意味着 GUI、CLI、analyzer、benchmark 以后都只能依赖这些对象，不能直接摸 engine 内部私有状态。

## 哪些面故意不开放

下面这些在 v1 明确不开放：

- `TurnState` 内部字段布局
- compact 具体 prompt 文本
- tool executor 的内部调度队列
- analytics sink 的落盘格式细节之外的实现细节
- lifecycle engine 的内部 stage helper 函数

这些都属于内核实现，不作为插件 surface。

## hook 面

v1 可以开放的 hook 只有事件型 hook，不开放“拿到 runtime 实例随便改”。

```python
class LifecycleHook(Protocol):
    async def __call__(self, event: LifecycleEvent) -> None: ...
```

允许的 hook 点：

- `before_model_call`
- `after_model_response`
- `after_tool_batch`
- `after_turn`

禁止的做法：

- hook 直接改 `SessionState.messages`
- hook 直接改 `MissionProfile`
- hook 直接跳过 policy gate

## provider 面

v1 的 provider 扩展面建议只允许“启动时注册”，不允许运行中热插拔：

- `MissionProfileProvider`
- `AnalyticsSink`
- `ModelClient`

原因很直接：v1 先把状态一致性做对，后面再谈动态加载。

## 为什么要像 Claude Code 一样收窄依赖面

Claude Code 的 `query/deps.ts` 说明了一个很实用的原则：

- 可替换的外部依赖要显式注入
- 不可替换的核心状态机留在 engine 内部

本项目必须照这个原则做，否则后续 GUI、benchmark、worker backend 一接入，就会把 runtime 内核撕开。

## 直接复用什么

- 复用 `query/deps.ts` 的窄依赖注入方式
- 复用 `Tool.ts` 的强类型工具协议
- 复用 `query/stopHooks.ts` 的事件型 hook 结构
- 复用 `QueryEngine.ts` 的“用 config + deps 构造 engine”思路

## 必须改写什么

- Claude Code 很多扩展面与 Bun feature gate、REPL、MCP 深耦合
  - 本项目要改成 Python protocol + provider 注册
- Claude Code 的部分扩展面默认围绕 coding session
  - 本项目必须围绕导出、分析、媒体恢复、审计任务
- Claude Code 的 worker 扩展面直接绑定 AgentTool
  - 本项目 v1 不引入 worker，因此不先暴露 worker backend API

## 当前 v1 实现什么

v1 只开放：

- provider 注册面
- hook 注册面
- model / tool / analytics / state store / profile 的抽象协议
- 启动时装配，不支持运行中变更

v1 不开放：

- 任意 Python 插件代码动态装载
- UI 插件直接操控 engine
- 第三方工具任意越权调用 NapCat 内部接口

## 后续再实现什么

后续再加：

- GUI adapter provider
- benchmark provider
- worker backend provider
- 只读插件 market surface
- profile bundle 导入导出

## 实现约束

1. 先做窄而稳的接口，不做宽而虚的“插件系统”。
2. 所有 extension surface 都必须经过 mission profile 和 mode 两层 gate。
3. 正式对外 surface 只能引用 `interfaces.py` 中声明的协议，不能引用私有 helper。
