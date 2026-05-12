# 共轨工作流共享上下文

## 目标

把共享 workflow 重构成一套：

- 能自我管理
- 先归档后改写
- 可严格审阅
- 能作为后续全项目重构母体工具

## 为什么要先做这一步

因为当前 workflow 虽然已经部分通用化，但仍有这些结构性缺口：

- 历史中心仍偏 exporter
- review state 分散在多个 ledger
- 用户审阅闸门还没制度化
- archive-first 还是实践，不是正式 contract

## 必须遵守的 Gate 顺序

1. Gate A：旧 workflow 摸底摘要
2. Gate B：第一版新架构草案
3. Gate C：reviewer 首轮严格批判
4. Gate D：worker 修正后的第二版
5. Gate E：最终人工放行

在这些 gate 通过前，不启动更广泛的 subsystem 重构。
