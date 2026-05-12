# Chat Orchestrator Mission Profiles 实现规范

## 目标

本文件定义 `MissionProfile`。它是 orchestrator 的任务配置层，负责把“要做什么”编码成结构化配置，而不是散落在 prompt 文本里。

推荐实现落点：

```text
src/qq_data_core/chat_orchestrator/
  mission_profiles.py
  profiles/
    watch_debug.py
    history_export.py
    message_first_analysis.py
    media_recovery_audit.py
```

## Claude Code 对照基线

本地 Claude Code 源码路径：

- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/QueryEngine.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/utils/queryContext.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/coordinator/coordinatorMode.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/bootstrap/state.ts`

本地 CC 解析文档：

- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/architecture_overview.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/migration_notes_for_shi_analyzer.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/file_index.md`

## MissionProfile 协议

v1 必须定义成代码配置对象，不用 YAML 自由发挥。

```python
@dataclass(frozen=True, slots=True)
class MissionProfile:
    profile_id: str
    description: str
    default_mode: str
    allowed_tools: tuple[str, ...]
    prompt_section_ids: tuple[str, ...]
    context_policy: ContextPolicy
    output_contract: OutputContract
    analytics_tags: dict[str, str]
```

`MissionProfile` 只声明配置，不直接执行逻辑。

## profile 装配顺序

v1 固定装配顺序：

1. 读取 `MissionProfile`
2. 解析 `RuntimeModeSpec`
3. 根据 profile 选择 tool allowlist
4. 根据 profile 选择 stable prompt sections
5. 根据 profile 选择 output schema

不要让 mode 反过来直接改 profile 本体。mode 只能覆盖 runtime 行为，不改 profile 定义。

## v1 profile 集合

v1 只实现四个 profile：

1. `watch_debug_v1`
   - 用于实时观察
   - 输出偏轻
   - 不做重型导出
2. `history_export_v1`
   - 用于历史导出
   - 允许导出 bundle 写盘
   - 允许媒体恢复工具
3. `message_first_analysis_v1`
   - 用于 message-first 分析 packet 生成
   - 输出结构化 analysis pack
4. `media_recovery_audit_v1`
   - 用于复核缺失资产
   - 输出 manifest 差异和缺口说明

这四个 profile 已覆盖当前仓库的主任务面，不需要在 v1 再加泛化 profile。

## profile 必须控制的字段

每个 profile 至少控制：

- `allowed_tools`
- `default_mode`
- `context_budget`
- `compact_strategy_id`
- `output_schema_id`
- `artifact_policy`

如果一个 profile 只改 prompt 文本，不改这些结构字段，它就不是合格的 profile。

## 与本仓库约束对齐

`history_export_v1` 和 `media_recovery_audit_v1` 必须内置以下约束：

- NapCat 只作为外部网关
- 正式媒体恢复只走 NapCat-only 路线
- 不依赖 NapCat 内部 TypeScript 模块
- 导出格式以 JSONL 为主，TXT 为辅

也就是说，仓库 AGENTS 里的约束必须进入 `MissionProfile` 的稳定前缀和 tool allowlist，而不是只停留在人工记忆。

## 直接复用什么

- 复用 `QueryEngine.ts` 的“先装配运行配置，再进入 engine”
- 复用 `utils/queryContext.ts` 的“上下文来自多段稳定 section 装配”
- 复用 `coordinatorMode.ts` 的“模式会补充不同 user context”思路
- 复用 `bootstrap/state.ts` 的“session 记录当前 profile/mode”

## 必须改写什么

- Claude Code 的 prompt section 主要围绕 coding assistant
  - 本项目必须改成 chat export / analysis / audit 的任务族
- Claude Code 的 profile-like 行为很多来自 feature gates 与 settings
  - 本项目 v1 要把 mission 配置显式收束到 `MissionProfile`
- Claude Code 的 coordinator profile 直接绑定多 worker
  - 本项目 v1 先不把 worker 语义放进 profile

## 当前 v1 实现什么

v1 只实现：

- 显式 `MissionProfile` dataclass
- 四个内建 profile
- profile 驱动的 tool allowlist / output contract / context policy
- profile 与 mode 分离

v1 不实现：

- 用户自定义 profile 热加载
- 外部 profile marketplace
- profile 级 worker 拓扑

## 后续再实现什么

后续再加：

- `benchmark_research_v2`
- `annotation_assist_v2`
- `coordinator_review_v2`
- profile inheritance
- profile version migration

## 实现约束

1. profile 只能描述任务配置，不能直接写业务副作用。
2. profile 标识要进入 state 与 analytics，方便回放。
3. 新增 profile 前，必须先证明它改变了结构化运行参数，而不是只改措辞。
