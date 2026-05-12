# 共轨工作流重构计划

状态：`phase_0_active`

## 范围

本阶段只重构 workflow 自身，不进入其他 subsystem 的大规模重构。

## Gate

- Gate A：旧 workflow 摸底与问题定义
- Gate B：第一版新架构草案
- Gate C：reviewer 首轮严格批判
- Gate D：worker 修正后的新草案
- Gate E：最终人工放行

## 退出条件

- workflow 拥有独立 program root
- archive-first 已被正式文档化并实际执行
- user checkpoint 已显式化
- reviewer / worker 轮次产物已制度化
- workflow 自身重构不再有 blocker
