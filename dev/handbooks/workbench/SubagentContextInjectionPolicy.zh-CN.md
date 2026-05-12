# Subagent 上下文注入策略

状态：`draft_round_003`

## 核心规则

subagent 不能只拿到一个局部小任务描述。

它必须同时拿到足够的战略上下文，理解：

- 为什么要做这个子任务
- 这个子任务服务于哪个更大的 program 目标
- 它受哪些规则和真相源约束
- 什么样的局部优化会变成坏优化

## 最低注入层

1. 局部任务范围
2. 当前 program 上下文
3. 必读真相源链
4. 当前 review 压力 / 已知 blocker
5. 战略目标与失败边界

## 强制 artifact

subagent 在正式执行前，必须至少拥有：

- `subagent_context_packet.json`
- 可选人类镜像：`subagent_context_packet.md`

其中最低字段至少包括：

- `program`
- `round`
- `task_scope`
- `parent_goal`
- `why_this_subtask_exists`
- `success_criteria`
- `failure_boundary`
- `must_read_files`
- `related_batches`
- `strategic_notes`
- `known_wrong_paths`
- `may_directly_challenge`

## 要避免的失败模式

不能把 subagent 训练成：

- 只会听局部命令
- 不知道为什么做
- 也不敢从第一性原理质疑局部命令

## validator 目标

validator 最终应能检查：

- context packet 是否存在
- 必填字段是否齐全
- packet 是否显式携带战略层语义，而不是只有局部 task 描述
