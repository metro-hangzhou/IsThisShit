# 技术路线图

对应 canonical 英文文件：

- [technical_roadmap.md](technical_roadmap.md)

对应 archive snapshot：

- `dev/archive/system_refactor_20260327/documents_repo_slice_20260327/source_snapshot/technical-roadmap.md`

## 这份文件在 cleaned 结构里的角色

它是：

- `repo-wide roadmap / historical planning report`

它不是：

- 某个子系统的 handbook
- 当前某一轮的执行 TODO

## 这份文件最重要的价值

它负责：

1. 描述仓库当前处于哪一阶段
2. 记录里程碑日志
3. 连接 exporter / preprocess / analysis / runtime / branching 几条大线
4. 给后续开发和回顾提供统一的大路线背景

## 为什么移出 `dev/documents/`

因为它和普通 report 不一样，它是 repo-wide 的大路线文档。  
继续混在 `dev/documents/` 会让：

- 分析报告
- 分支治理
- repo 大路线

三种不同职责继续搅在一起。

## 当前增量提醒

这轮清洗后，和这份 repo-wide roadmap 直接相关的新 canonical surface 还包括：

- [../napcat/INDEX.zh-CN.md](../napcat/INDEX.zh-CN.md)
- [../napcat/runtime_surface.zh-CN.md](../napcat/runtime_surface.zh-CN.md)
- [../napcat/runtime_state_and_plugins.zh-CN.md](../napcat/runtime_state_and_plugins.zh-CN.md)

这意味着原计划里的 `NapCat runtime` 这一段，已经不再只是零散 runtime 修修补补，而是有了独立的 surface map。
