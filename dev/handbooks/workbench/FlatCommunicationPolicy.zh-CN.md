# 扁平化沟通政策

状态：`draft_round_003`

## 核心规则

只要 evidence 或第一性原理判断表明某个局部规则、任务 framing 或实现路径有问题，workflow 上的任何单元都可以通过结构化文件系统产物直接挑战另一个单元。

## 适用对象

- reviewer
- explorer
- worker
- main agent
- subagents

## 允许直接挑战的目标

- reviewer 结论
- worker 草案假设
- main agent 的任务 framing
- subagent 的局部 task framing

## 约束

扁平沟通必须保持：

- 结构化
- 可追责
- 文件化
- 可审阅

而不是随意插话式沟通。

## 强制 artifact

扁平化沟通至少要有一个 canonical 载体：

- `challenge_register.json`

可选人类镜像：

- `cross_role_challenges.md`
- `objection_or_fast_fail_notice.md`

只要系统里允许直接异议，就必须有可追溯的 challenge 载体。

## 必须响应

扁平化沟通不是“允许你提”，而是：

- 提出的结构化 challenge 不能被静默忽略
- reviewer 必须显式处理 challenge
- main agent 对 `task_framing_objection` 必须显式回应

## 参考范式

见：

- [ElonMuskReferenceModel.zh-CN.md](ElonMuskReferenceModel.zh-CN.md)

这里借用的不是某家公司完整管理制度，而是其中最重要的一条精神：

- 只要异议是有证据、有因果链、有目标忠诚度的，就应允许直接抵达真正能改事的人和层
