# 共轨工作流 Program

## 目的

这个 program 专门负责重构共享 reviewer / explorer / worker 工作流本身。

它存在的原因是：

- 让 workflow 自己也被同样严格的制度管理
- 让后续全项目重构建立在一个先被审过、先被留档过的 workflow 之上

## 当前阶段

- `phase_0_workflow_refactor`
- `archive_first`
- `user_gated`
- 在它通过前，不启动更广义的仓库重构

## 真相源

1. `AGENTS.md`
2. `dev/agents/subagents/CONTRACT.md`
3. `dev/agents/subagents/SHARED_CONTEXT.md`
4. `dev/agents/programs/**`
5. `dev/todos/programs/**`
6. `state/reviewer_runs/**`
7. `state/program_runs/**`

## 不可谈判规则

- 改 workflow 前先归档
- 不删除旧 workflow 产物
- 不允许默认把用户闸门视为已通过
- reviewer 输出必须保持结构化
- worker 响应必须明确、按轮次留痕

## 开发执行形式

- 轻任务允许主 agent 直接本地完成，不强制起 subagents
- 这里的轻任务指：
  - 单文件或低耦合改动
  - 局部 UI 微调
  - 不改变跨模块契约、不显著扩大测试面的小修
- 较重任务必须走共轨工作流下的 subagents 并发
- 这里的较重任务指：
  - 跨组件 / 跨子系统改动
  - 需要结构化 reviewer 批判或 blocker 复核的任务
  - 会改变 runtime、数据契约、资源链、主交互结构或验证面的批次
- 对较重任务，主 agent 默认负责：
  - 明确任务重量级判断
  - 发起并行 reviewer / explorer / worker 轨
  - 集成结果
  - 跑最终验收与文档回填
- 当前额外模型策略：
  - 只要起 subagents，一律使用 `gpt-5.5`
  - 推理强度一律使用 `xhigh`
  - 不允许因为成本、速度或习惯临时降到其他模型或更低推理强度
- 不允许把本应走并发共轨的较重任务，伪装成普通顺手小修单线完成
