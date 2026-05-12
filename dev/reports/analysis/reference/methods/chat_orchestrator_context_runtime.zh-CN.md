# Chat Orchestrator Context Runtime 实现规范

## 目标

本文件定义 `chat_orchestrator` 的 context runtime，解决三件事：

1. 稳定前缀怎么组
2. 每轮 turn 的动态 packet 怎么组
3. 超预算时按什么顺序裁剪与 compact

推荐实现落点：

```text
src/qq_data_core/chat_orchestrator/
  context.py
  budget.py
  memory.py
```

## Claude Code 对照基线

本地 Claude Code 源码路径：

- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/context.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/utils/queryContext.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/services/compact/autoCompact.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/services/compact/compact.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/services/compact/prompt.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/services/SessionMemory/sessionMemory.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/services/compact/sessionMemoryCompact.ts`
- `/mnt/d/Coding_Project/IsThisShit/claude-code/src/utils/contextAnalysis.ts`

本地 CC 解析文档：

- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/context_and_compaction.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/file_index.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/function_index.md`
- `/mnt/d/Coding_Project/IsThisShit/dev/reports/analysis/reference/claude_code/migration_notes_for_shi_analyzer.md`

## 实现对象

v1 只定义三个核心对象：

```python
@dataclass(slots=True)
class StablePrefix:
    cache_key: str
    sections: list[PromptSection]


@dataclass(slots=True)
class ContextPacket:
    stable_prefix: StablePrefix
    dynamic_sections: list[PromptSection]
    compact_summary: str | None
    source_stats: ContextSourceStats


@dataclass(slots=True)
class ContextBudget:
    max_input_tokens: int
    reserved_output_tokens: int
    trim_order: tuple[str, ...]
```

`PromptSection` 必须带 `section_id`、`source_kind`、`content`、`priority`，否则后面无法做源级裁剪和 analytics。

## 稳定前缀怎么组

稳定前缀只能包含慢变内容：

- mission profile 固定说明
- 输出 schema
- 本项目的领域约束
- 已确认的长期 session memory
- 当前 mode 的稳定规则

不要把以下内容放入稳定前缀：

- 本轮新收到的聊天消息
- 临时 tool result
- 最近一次导出统计
- 仅对当前 turn 生效的补丁指令

推荐 builder：

```python
class StablePrefixBuilder:
    def build(self, profile: MissionProfile, mode: RuntimeMode) -> StablePrefix: ...
```

缓存 key 建议包含：

- `profile_id`
- `mode_id`
- `profile_version`
- `policy_revision`

## 动态 packet 怎么组

动态 packet 在 v1 只装四类内容：

1. 当前 turn 的用户目标
2. 本轮新增消息或增量消息图
3. 与本轮相关的 tool state 摘要
4. 已存在的 compact summary

推荐 builder：

```python
class ContextPacketBuilder:
    def build_turn_packet(
        self,
        session_state: SessionState,
        request: OrchestratorRequest,
        budget: ContextBudget,
    ) -> ContextPacket: ...
```

v1 不允许“把整段 transcript 全塞进 packet 再看模型能不能吃下”。packet 组装时就要按 source kind 分类。

## 预算与裁剪顺序

`ContextBudget` 必须在 packet 构建前确定，不能等模型报错后再现算。

推荐固定顺序：

1. 先保留 `stable_prefix`
2. 再保留 `current_objective`
3. 再保留 `direct_message_evidence`
4. 再保留 `relation_bound_context`
5. 再保留 `tool_state`
6. 最后才保留 `weak_boundary_context`

超预算时裁剪顺序固定：

1. `weak_boundary_context`
2. `repeated_tool_output`
3. `carrier_only_or_duplicate_evidence`
4. `older_compact_suffix`

禁止把 `stable_prefix` 和 `current_objective` 当成兜底垃圾位处理。

## compact 规则

compact 的输出不是“随便一段摘要”，而是可重新注入的 continuation state。

推荐最小结构：

```python
@dataclass(slots=True)
class CompactSummary:
    established_facts: list[str]
    unresolved_questions: list[str]
    active_artifacts: list[str]
    dropped_noise_classes: list[str]
```

compact prompt 也必须按这个结构产出，不能回退成自由文本大段总结。

## source stats

v1 必须把 token 或字符预算按 source kind 统计。至少要区分：

- `stable_prefix`
- `current_objective`
- `message_evidence`
- `relation_context`
- `tool_results`
- `compact_summary`

这部分实现建议直接放在 `context.py`，不要散到 analytics sink 里再反推。

## 直接复用什么

- 复用 `context.ts` 的“稳定前缀缓存”思想
- 复用 `utils/queryContext.ts` 的“所有 query 路径都必须复建同一前缀”原则
- 复用 `autoCompact.ts` 的“先预留输出预算，再算可用输入窗口”
- 复用 `compact.ts` 的“compact 后返回边界 + summary + kept suffix”的结构
- 复用 `contextAnalysis.ts` 的“按 source class 计 token”的方法
- 复用 `sessionMemory.ts` / `sessionMemoryCompact.ts` 的“session memory 优先于传统 compact”的优先级思路

## 必须改写什么

- Claude Code 的 `gitStatus`、`CLAUDE.md`、memory files 不能原样沿用
  - 本项目要替换成 mission profile、导出规范、analysis pack 规则、chat state
- Claude Code 的 strip 逻辑主要面向图片和文档附件
  - 本项目要改成面向重复消息壳、重复 artifact、低价值 boundary context
- Claude Code 的 compact prompt 面向编码继续工作
  - 本项目要改成面向聊天理解、导出恢复、analyzer continuation

## 当前 v1 实现什么

v1 只实现：

- 稳定前缀 builder
- turn packet builder
- 固定预算模型
- 固定裁剪顺序
- 结构化 compact summary
- source stats 统计

v1 不实现：

- 后台 session memory 抽取
- reactive compact
- context collapse
- 多版本 compact strategy 并存

## 后续再实现什么

后续再加：

- session memory 后台更新
- packet 局部 collapse
- 不同 mission profile 的差异化 compact strategy
- compact 自身过长时的二级降级梯度
- 可审计的 context diff 输出

## 实现约束

1. context runtime 只能输出结构化 `ContextPacket`，不能直接去调模型。
2. budget 规则必须是纯函数，方便后续 benchmark。
3. compact summary 必须能脱离原 transcript 继续工作，不能依赖“读者知道前文”。
