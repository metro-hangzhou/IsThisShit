# 引用与路由校验

状态：`draft_round_002`

## 作用

让“先路由、再读链、再引用”这件事在事后可被审计，而不是只停留在口头承诺。

## 必需证据

- `resolved_truth_sources.json`
- `truth_source_usage.json`

## 适用层级

这条校验同时适用于：

- round 级
- subagent 级

只要某个单元在实质性地做任务，它就必须留下 routing 与 usage 证据。

## `truth_source_usage.json` 最低字段

- `resolved_truth_sources_ref`
- `files_read`
- `files_cited`
- `claims_to_sources`

## reviewer 执法点

reviewer 可以针对下面情况提出 blocker：

- 必读文件没有被读取
- 关键结论没有来源支持
- 辅助报告被当成主真相源引用

对应 blocker 类别：

- `routing_fidelity`
- `citation_integrity`

## subagent 级最低要求

对 subagent 来说，至少要满足：

- 要么有自己的 `resolved_truth_sources.*` / `truth_source_usage.*`
- 要么在 `subagent_context_packet` 中明确引用继承来源，并在本地 usage 里留下 `files_read` / `files_cited` / `claims_to_sources`

否则 routing 仍然只是 round ritual，不算真正落地。
