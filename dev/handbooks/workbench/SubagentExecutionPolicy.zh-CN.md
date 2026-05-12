# Subagents 优先执行策略

状态：`draft_round_002`

## 核心规则

默认采用 `subagents-first` 的执行方式。

## 覆盖判据

这条规则不能只靠“派了几个 subagent”来假装满足。

至少要回答：

- 哪类任务默认必须拆
- 哪类任务允许 main agent 本地直做
- 偏离默认策略时是否有留痕

默认必须拆的任务类型至少包括：

- 多维审查
- 跨文件制度设计
- 需要多种独立批判视角的架构问题
- 需要并行读取多个真相源的任务

允许 main agent 本地直做的任务类型至少包括：

- 当前轮次的最终整合
- reviewer 包打包
- broad regression / 总测试
- 高耦合且立即阻塞的单点修正

## 默认模型策略

- 默认下发模型：`gpt-5.5`
- 默认推理强度：`xhigh`

## main agent 的主职责

main agent 应主要负责：

- 任务分批与分类
- 下发 subagents
- 整合输出
- 做验收检查
- 做总回归和最终验证

main agent 不应在可以安全委派时，长期垄断细节探索和草稿生成工作。

## 例外情况

以下情况可以由 main agent 本地处理：

- 当前任务阻塞下一步
- 写入范围高度耦合
- 委派会导致重复劳动或明显的合并风险

## 强制 artifact

与这条政策配套的最低运行态产物包括：

- `task_dispatch_plan.md`
- `subagent_execution_ledger.json`
- `main_agent_action_ledger.md`

## 不允许的假并行

下面这些不算真正满足 `subagents-first`：

- 机械地只派一个无关紧要的 subagent
- main agent 实际做了 90% 工作，subagent 只做点缀
- 明明适合拆分，却因为习惯而继续由 main agent 独占

## 参考范式

见：

- [ElonMuskReferenceModel.zh-CN.md](ElonMuskReferenceModel.zh-CN.md)

subagents-first 的真正目标不是“多开几个 agent 看起来很并行”，而是：

- 让更多单元拥有独立判断能力
- 让 main agent 不再成为大包大揽的中心工头
- 让系统更接近高比率、低官僚、直接面向目标的工程组织
