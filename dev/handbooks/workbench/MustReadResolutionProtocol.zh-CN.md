# 必读链解析协议

状态：`draft_round_002`

## 必需产物

每一轮在 worker 进入正式输出前，都必须先解析出本轮的必读集。

必需文件：

- `resolved_truth_sources.json`
- `resolved_truth_sources.md`

## 适用层级

这条协议同时适用于：

- round 级
- subagent 级

也就是说：

- 不只是整个 round 要先解析必读链
- 每个真正执行子任务的 subagent 也必须继承或生成自己的必读链解析结果

## 最低字段

- `task_scope`
- `resolved_domains`
- `must_read_files`
- `expanded_files`
- `missing_required_files`
- `routing_status`

## 规则

- `must_read_files` 必须能从路由注册表和任务范围确定性推导出来
- `missing_required_files` 不能被静默忽略
- 如果 routing 不是 `ready`，该轮最多只能继续做 blocked 或 design-only 模式，不得宣称完成
- subagent 级至少必须满足二选一：
  - A. 自己拥有 `resolved_truth_sources.json`
  - B. 拥有继承式 `subagent_context_packet`，并明确记录 `resolved_truth_sources_ref`
