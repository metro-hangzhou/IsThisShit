# 分支同步事故记录

对应 canonical 英文文件：

- [branch_sync_incidents.md](branch_sync_incidents.md)

对应 archive snapshot：

- `dev/archive/system_refactor_20260327/documents_branching_slice_20260327/source_snapshot/branch-sync-incidents.md`

## 这份文件在 cleaned 结构里的角色

它是：

- `branching incident report`

而不是：

- 一般技术说明
- 通用开发计划

## 它最重要的作用

记录这些类型的事故：

- release line bundle skew
- partial cherry-pick
- launcher/runtime family drift
- auto-update 拉到半新半旧状态

## 为什么必须和 branching plan 放在一起

因为：

- `git_branching_plan` 负责“制度”
- `branch_sync_incidents` 负责“事故记忆”

这两者一起才构成真正的 branch governance 面。
