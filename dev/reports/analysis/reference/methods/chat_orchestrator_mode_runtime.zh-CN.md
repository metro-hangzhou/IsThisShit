# Chat Orchestrator Mode Runtime 实现规范

## 目标

本文件定义 orchestrator 的“运行模式”而不是“mission profile”。mode 负责运行时行为切换，mission profile 负责任务配置。两者必须分离。

推荐实现落点：

```text
src/qq_data_core/chat_orchestrator/
  modes.py
  mode_state.py
```

## Claude Code 对照基线

本地 Claude Code 源码路径：

- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/commands/plan/plan.tsx`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/coordinator/coordinatorMode.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/bootstrap/state.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/utils/permissions/permissionSetup.ts`

本地 CC 解析文档：

- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/planning_execution_permissions.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/architecture_overview.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/file_index.md`

## mode 与 mission profile 的边界

必须把这两个概念拆开：

- `mission profile`
  - 决定任务目标、输出 schema、工具白名单、默认预算
- `runtime mode`
  - 决定交互形态、是否允许计划编辑、是否允许自动执行、失败时是否 fail-closed

不要把 `historical_export`、`message_first_analysis` 这种任务名直接做成 mode。

## v1 mode 集合

v1 只定义四个 mode：

1. `interactive`
   - 允许多轮对话
   - 允许计划更新
   - 允许工具调用
2. `plan`
   - 只允许产出计划或修改计划
   - 禁止执行副作用型工具
3. `batch_headless`
   - 无人工确认
   - 失败直接返回结构化错误
4. `strict_audit`
   - 工具白名单更窄
   - 输出必须包含证据路径和不确定性

## mode 结构

```python
@dataclass(frozen=True, slots=True)
class RuntimeModeSpec:
    mode_id: str
    allow_mutating_tools: bool
    allow_plan_write: bool
    avoid_interactive_prompts: bool
    require_structured_output: bool
    fail_closed: bool
```

`modes.py` 只导出 `MODE_SPECS` 和转换函数，不直接碰 session store。

## mode 解析优先级

v1 固定优先级：

1. 显式请求参数
2. 已恢复 session 的持久化 mode
3. mission profile 默认值
4. 仓库默认 `interactive`

一旦本轮选择完成，要把最终 mode 写回 `SessionState.mode`，不能只放在局部变量里。

## mode 转换规则

v1 只允许这些转换：

- `interactive -> plan`
- `plan -> interactive`
- `interactive -> strict_audit`
- `batch_headless -> strict_audit`

v1 不允许：

- `batch_headless -> interactive`
- `plan -> batch_headless` 自动跳转
- 任意 mode 自动进入 `coordinator`

mode 转换必须是显式 API，不要让 tool executor 私自改 mode。

## mode 对 runtime 的影响

mode 至少影响以下四项：

1. `context`
   - plan 模式只注入计划上下文
2. `tools`
   - 是否允许副作用型工具
3. `output contract`
   - 是否强制结构化输出
4. `failure policy`
   - 是可恢复提示，还是 fail-closed

如果一个 mode 不改变以上任意一项，它就不应作为单独 mode 存在。

## 计划模式实现

像 Claude Code 一样，plan mode 入口必须很薄：

- 切 mode
- 载入 plan artifact
- 把计划写回 session state

真正的计划生成依然走 engine，而不是在 `modes.py` 自己拼 prompt。

推荐 plan artifact 路径：

- `state/chat_orchestrator/plans/<session_id>.md`

## 直接复用什么

- 复用 `plan.tsx` 的“plan 是 regime change，不是 prompt tweak”
- 复用 `coordinatorMode.ts` 的“mode 会影响 user context 与 system prompt”
- 复用 `bootstrap/state.ts` 的“mode 状态写入 session 级 state”
- 复用 `permissionSetup.ts` 的“mode 会改权限上下文”这个设计模式

## 必须改写什么

- Claude Code 的 mode 切换靠 slash command 与 REPL UI
  - 本项目必须改成纯 API / runtime 调用
- Claude Code 的 mode 大量围绕 coding 权限
  - 本项目要改成导出、分析、审计的域内规则
- Claude Code 的 `coordinator` 直接绑定 subagent 体系
  - 本项目 v1 不引入 worker，所以不能先抄 coordinator mode

## 当前 v1 实现什么

v1 只实现：

- `interactive`
- `plan`
- `batch_headless`
- `strict_audit`
- 显式 mode spec
- 显式 mode transition API

v1 不实现：

- `coordinator`
- `worker`
- auto mode classifier
- mode 内嵌的异步审批链

## 后续再实现什么

后续再加：

- `coordinator` 与 `worker` mode
- profile 驱动的 mode constraints
- mode-aware cache policy
- mode-aware compact strategy
- 恢复旧 session 时的 mode 自动对齐提示

## 实现约束

1. mode 只描述运行时行为，不描述任务目的。
2. mode 切换必须可审计，写进 state 与 analytics。
3. 任何工具都不能绕开 `RuntimeModeSpec` 直接执行禁用动作。
