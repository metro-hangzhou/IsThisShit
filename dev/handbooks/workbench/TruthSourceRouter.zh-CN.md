# 真相源路由器

状态：`draft_round_002`

## 作用

定义 workflow 如何在实质工作开始前，先解析出本轮任务必须阅读的文档链。

## 核心规则

如果一轮任务没有先产出：

- `resolved_truth_sources.json`
- `truth_source_usage.json`

那么这轮任务不算有效进入实质执行。

## 路由职责

- 识别任务所属领域
- 展开 must-read 文档链
- 标记缺失的必需文件
- 把确定性的阅读义务下发给 worker 与 subagents

## 路由优先级

1. 仓库根级总手册
2. 领域手册
3. program 级手册
4. 辅助计划与报告

## 执行约束

- validator 要检查 routing artifacts 是否存在
- reviewer 可以提出 `routing_fidelity` blocker
- 只要路由未闭合，这轮就不能算关闭
